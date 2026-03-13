"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import type {
  ProjectSummary,
  SessionResponse,
  ShellState
} from "@ukde/contracts";
import { resolveAdaptiveShellState } from "@ukde/contracts";
import {
  accessTierBadgeTones,
  accessTierLabels,
  environmentLabels,
  shellStateNotes
} from "@ukde/ui";

import { ThemePreferenceControl } from "./theme-preference-control";

interface AuthenticatedShellProps {
  children: React.ReactNode;
  csrfToken: string | null;
  projects: ProjectSummary[];
  session: SessionResponse;
}

interface NavLink {
  href: string;
  label: string;
  requiresProjectMembership?: boolean;
  requiresSettingsAccess?: boolean;
}

const GLOBAL_NAV_LINKS: NavLink[] = [
  { href: "/projects", label: "Projects" },
  { href: "/activity", label: "My activity" }
];

const PROJECT_CONTEXT_LINKS: NavLink[] = [
  { href: "overview", label: "Overview", requiresProjectMembership: true },
  { href: "documents", label: "Documents", requiresProjectMembership: true },
  { href: "jobs", label: "Jobs", requiresProjectMembership: true },
  {
    href: "export-candidates",
    label: "Export candidates",
    requiresProjectMembership: true
  },
  {
    href: "export-requests",
    label: "Export requests",
    requiresProjectMembership: true
  },
  {
    href: "export-review",
    label: "Export review",
    requiresProjectMembership: true
  },
  { href: "activity", label: "Activity", requiresProjectMembership: true },
  { href: "settings", label: "Settings", requiresSettingsAccess: true }
];

const ADMIN_CONTEXT_LINKS: NavLink[] = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/audit", label: "Audit" },
  { href: "/admin/security", label: "Security" },
  { href: "/admin/operations", label: "Operations" },
  { href: "/admin/design-system", label: "Design system" }
];

function isActiveRoute(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function resolveEnvironmentLabel(): string {
  const raw = process.env.NEXT_PUBLIC_APP_ENV ?? process.env.APP_ENV ?? "dev";
  const normalized = raw.toLowerCase();
  if (normalized in environmentLabels) {
    return environmentLabels[normalized as keyof typeof environmentLabels];
  }
  return raw;
}

function resolveShellHeading(pathname: string): string {
  if (pathname.startsWith("/projects/")) {
    return "Project workspace";
  }
  if (pathname.startsWith("/projects")) {
    return "Projects";
  }
  if (pathname.startsWith("/admin")) {
    return "Admin workspace";
  }
  if (pathname.startsWith("/activity")) {
    return "My activity";
  }
  return "Secure workspace";
}

function resolveTaskContext(pathname: string): "dense" | "standard" {
  if (pathname.includes("/viewer")) {
    return "dense";
  }
  return "standard";
}

export function AuthenticatedShell({
  children,
  csrfToken,
  projects,
  session
}: AuthenticatedShellProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [shellState, setShellState] = useState<ShellState>("Expanded");
  const isAdmin = session.user.platformRoles.includes("ADMIN");
  const hasPlatformRole = session.user.platformRoles.length > 0;
  const forceFocus = searchParams.get("shell") === "focus";

  const currentProject = useMemo(() => {
    const pathSegments = pathname.split("/").filter(Boolean);
    if (pathSegments[0] !== "projects" || !pathSegments[1]) {
      return null;
    }
    return projects.find((project) => project.id === pathSegments[1]) ?? null;
  }, [pathname, projects]);

  useEffect(() => {
    const syncShellState = () => {
      setShellState(
        resolveAdaptiveShellState({
          viewportWidth: window.innerWidth,
          viewportHeight: window.innerHeight,
          forceFocus,
          taskContext: resolveTaskContext(pathname)
        })
      );
    };

    syncShellState();
    window.addEventListener("resize", syncShellState);
    return () => window.removeEventListener("resize", syncShellState);
  }, [forceFocus, pathname]);

  const globalNavLinks = hasPlatformRole
    ? [...GLOBAL_NAV_LINKS, { href: "/admin", label: "Admin" }]
    : GLOBAL_NAV_LINKS;

  const visibleProjectLinks = PROJECT_CONTEXT_LINKS.filter((link) => {
    if (!currentProject) {
      return false;
    }
    if (link.requiresProjectMembership && !currentProject.isMember) {
      return false;
    }
    if (link.requiresSettingsAccess && !currentProject.canAccessSettings) {
      return false;
    }
    return true;
  });

  const showProjectContext =
    pathname.startsWith("/projects/") && currentProject;
  const showAdminContext = pathname.startsWith("/admin");
  const showContextRegion =
    shellState === "Expanded" || (shellState === "Balanced" && !forceFocus);

  return (
    <div className="authenticatedShell" data-shell-state={shellState}>
      <a className="ukde-skip-link" href="#ukde-shell-work-region">
        Skip to work region
      </a>

      <header className="authenticatedShellHeader ukde-panel">
        <div className="authenticatedShellIdentity">
          <p className="ukde-eyebrow">UKDataExtraction (UKDE)</p>
          <p className="authenticatedShellTitle">
            {resolveShellHeading(pathname)}
          </p>
          {currentProject ? (
            <p className="ukde-muted">Project: {currentProject.name}</p>
          ) : null}
        </div>

        <div className="authenticatedShellActions">
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

          <ThemePreferenceControl className="workspaceThemeControl" />

          <div className="workspaceBadges">
            <span className="ukde-badge">Env {resolveEnvironmentLabel()}</span>
            {currentProject ? (
              <span
                className="ukde-badge"
                data-tone={
                  accessTierBadgeTones[currentProject.intendedAccessTier]
                }
              >
                Tier {accessTierLabels[currentProject.intendedAccessTier]}
              </span>
            ) : (
              <span className="ukde-badge">Tier CONTROLLED</span>
            )}
            <span className="ukde-badge">{shellState}</span>
          </div>

          <details className="workspaceMenu">
            <summary className="workspaceMenuTrigger">
              {session.user.displayName}
            </summary>
            <div className="workspaceMenuPanel">
              <span className="ukde-muted">{session.user.email}</span>
              <span className="ukde-muted">
                {hasPlatformRole
                  ? session.user.platformRoles.join(", ")
                  : "No platform-role override"}
              </span>
              <Link href="/activity">My activity</Link>
              <form action="/auth/logout" method="post">
                <input
                  name="csrf_token"
                  type="hidden"
                  value={csrfToken ?? ""}
                />
                <button className="workspaceSignOutButton" type="submit">
                  Sign out
                </button>
              </form>
            </div>
          </details>
        </div>
      </header>

      <div className="authenticatedShellGrid">
        <aside className="authenticatedShellRail ukde-panel">
          <p className="ukde-eyebrow">Navigation</p>
          <nav aria-label="Primary navigation">
            <ul className="authenticatedShellRailList">
              {globalNavLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    aria-current={
                      isActiveRoute(pathname, link.href) ? "page" : undefined
                    }
                    className="authenticatedShellRailLink"
                    href={link.href}
                  >
                    <span
                      aria-hidden
                      className="authenticatedShellRailLinkShort"
                    >
                      {link.label.slice(0, 1)}
                    </span>
                    <span className="authenticatedShellRailLinkLabel">
                      {link.label}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </aside>

        <section className="authenticatedShellMain">
          {showProjectContext && shellState !== "Focus" ? (
            <nav
              aria-label="Project context"
              className="projectContextBar ukde-panel"
            >
              <ul className="authenticatedShellContextList">
                {visibleProjectLinks.map((link) => {
                  const href = `/projects/${currentProject.id}/${link.href}`;
                  return (
                    <li key={link.href}>
                      <Link
                        aria-current={
                          isActiveRoute(pathname, href) ? "page" : undefined
                        }
                        className="authenticatedShellContextLink"
                        href={href}
                      >
                        {link.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </nav>
          ) : null}

          {showProjectContext && shellState === "Focus" ? (
            <details className="shellContextDrawer ukde-panel">
              <summary className="shellContextDrawerTrigger">
                Project context
              </summary>
              <nav aria-label="Project context">
                <ul className="authenticatedShellContextList">
                  {visibleProjectLinks.map((link) => {
                    const href = `/projects/${currentProject.id}/${link.href}`;
                    return (
                      <li key={link.href}>
                        <Link
                          aria-current={
                            isActiveRoute(pathname, href) ? "page" : undefined
                          }
                          className="authenticatedShellContextLink"
                          href={href}
                        >
                          {link.label}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </nav>
            </details>
          ) : null}

          {showAdminContext && shellState !== "Focus" ? (
            <nav
              aria-label="Admin context"
              className="adminContextBar ukde-panel"
            >
              <ul className="authenticatedShellContextList">
                {ADMIN_CONTEXT_LINKS.map((link) => (
                  <li key={link.href}>
                    <Link
                      aria-current={
                        isActiveRoute(pathname, link.href) ? "page" : undefined
                      }
                      className="authenticatedShellContextLink"
                      href={link.href}
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ) : null}

          {showAdminContext && shellState === "Focus" ? (
            <details className="shellContextDrawer ukde-panel">
              <summary className="shellContextDrawerTrigger">
                Admin context
              </summary>
              <nav aria-label="Admin context">
                <ul className="authenticatedShellContextList">
                  {ADMIN_CONTEXT_LINKS.map((link) => (
                    <li key={link.href}>
                      <Link
                        aria-current={
                          isActiveRoute(pathname, link.href)
                            ? "page"
                            : undefined
                        }
                        className="authenticatedShellContextLink"
                        href={link.href}
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            </details>
          ) : null}

          <div
            className="authenticatedShellWorkRegion"
            id="ukde-shell-work-region"
            tabIndex={-1}
          >
            {children}
          </div>
        </section>

        {showContextRegion ? (
          <aside className="authenticatedShellContext ukde-panel">
            <p className="ukde-eyebrow">Adaptive state</p>
            <h2>{shellState}</h2>
            <p className="ukde-muted">{shellStateNotes[shellState]}</p>
            <ul className="projectMetaList">
              <li>
                <span>Task context</span>
                <strong>{resolveTaskContext(pathname)}</strong>
              </li>
              <li>
                <span>Focus override</span>
                <strong>{forceFocus ? "enabled" : "off"}</strong>
              </li>
              <li>
                <span>Role mode</span>
                <strong>{isAdmin ? "ADMIN" : "STANDARD"}</strong>
              </li>
            </ul>
            <p className="ukde-muted">
              Keyboard path: <span className="ukde-kbd">Tab</span> through rail,
              context bar, then work region.
            </p>
          </aside>
        ) : null}
      </div>
    </div>
  );
}
