"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import type {
  PlatformRole,
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
import { StatusChip } from "@ukde/ui/primitives";

import {
  activityPath,
  adminPath,
  approvedModelsPath,
  projectDerivativesPath,
  projectEntitiesPath,
  healthPath,
  projectIndexesPath,
  projectModelAssignmentsPath,
  projectPoliciesPath,
  projectPseudonymRegistryPath,
  projectSearchPath,
  projectsPath
} from "../lib/routes";
import { GlobalCommandBar } from "./global-command-bar";
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
  requiresAnyPlatformRole?: PlatformRole[];
  requiresProjectMembership?: boolean;
  requiresSettingsAccess?: boolean;
}

const GLOBAL_NAV_LINKS: NavLink[] = [
  { href: projectsPath, label: "Projects" },
  { href: activityPath, label: "My activity" }
];

const PROJECT_CONTEXT_LINKS: NavLink[] = [
  { href: "overview", label: "Overview", requiresProjectMembership: true },
  { href: "documents", label: "Documents", requiresProjectMembership: true },
  {
    href: "model-assignments",
    label: "Model assignments",
    requiresProjectMembership: true
  },
  { href: "search", label: "Search", requiresProjectMembership: true },
  { href: "entities", label: "Entities", requiresProjectMembership: true },
  { href: "derivatives", label: "Derivatives", requiresProjectMembership: true },
  { href: "indexes", label: "Indexes", requiresProjectMembership: true },
  { href: "policies", label: "Policies", requiresProjectMembership: true },
  {
    href: "pseudonym-registry",
    label: "Pseudonym registry",
    requiresProjectMembership: true
  },
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

function resolveEnvironmentTone(): "neutral" | "warning" | "success" | "info" {
  const raw = process.env.NEXT_PUBLIC_APP_ENV ?? process.env.APP_ENV ?? "dev";
  const normalized = raw.toLowerCase();
  if (normalized === "prod") {
    return "success";
  }
  if (normalized === "staging") {
    return "info";
  }
  if (normalized === "dev") {
    return "warning";
  }
  return "neutral";
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

function resolveProjectContextHref(projectId: string, linkHref: string): string {
  if (linkHref === "model-assignments") {
    return projectModelAssignmentsPath(projectId);
  }
  if (linkHref === "indexes") {
    return projectIndexesPath(projectId);
  }
  if (linkHref === "search") {
    return projectSearchPath(projectId);
  }
  if (linkHref === "entities") {
    return projectEntitiesPath(projectId);
  }
  if (linkHref === "derivatives") {
    return projectDerivativesPath(projectId);
  }
  if (linkHref === "policies") {
    return projectPoliciesPath(projectId);
  }
  if (linkHref === "pseudonym-registry") {
    return projectPseudonymRegistryPath(projectId);
  }
  return `/projects/${projectId}/${linkHref}`;
}

function resolveOpenDetailsLayers(): HTMLDetailsElement[] {
  return Array.from(
    document.querySelectorAll<HTMLDetailsElement>(
      ".workspaceMenu[open], .shellContextDrawer[open], .pageHeaderOverflow[open]"
    )
  );
}

export function AuthenticatedShell({
  children,
  csrfToken,
  projects,
  session
}: AuthenticatedShellProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const workRegionRef = useRef<HTMLDivElement | null>(null);
  const previousRouteKeyRef = useRef<string | null>(null);
  const [shellState, setShellState] = useState<ShellState>("Expanded");
  const isAdmin = session.user.platformRoles.includes("ADMIN");
  const isAuditor = session.user.platformRoles.includes("AUDITOR");
  const roleModeLabel = isAdmin ? "ADMIN" : isAuditor ? "AUDITOR" : "STANDARD";
  const hasPlatformRole = session.user.platformRoles.length > 0;
  const canViewApprovedModels =
    isAdmin ||
    projects.some(
      (project) =>
        project.currentUserRole === "PROJECT_LEAD" ||
        project.currentUserRole === "REVIEWER"
    );
  const forceFocus = searchParams.get("shell") === "focus";
  const searchKey = searchParams.toString();

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

  useEffect(() => {
    const routeKey = `${pathname}?${searchKey}`;
    if (previousRouteKeyRef.current === null) {
      previousRouteKeyRef.current = routeKey;
      return;
    }
    if (previousRouteKeyRef.current === routeKey) {
      return;
    }
    const activeElement =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const shouldMoveFocus = Boolean(
      activeElement?.closest(
        [
          ".authenticatedShellRail",
          ".projectContextBar",
          ".adminContextBar",
          ".shellContextDrawer",
          ".workspaceMenu",
          ".globalCommandControls"
        ].join(",")
      )
    );
    if (shouldMoveFocus) {
      workRegionRef.current?.focus({ preventScroll: true });
    }
    previousRouteKeyRef.current = routeKey;
  }, [pathname, searchKey]);

  useEffect(() => {
    const handleEscapeDismiss = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }
      const layers = resolveOpenDetailsLayers();
      if (layers.length === 0) {
        return;
      }
      const topmost = layers[layers.length - 1];
      topmost.open = false;
      const summary = topmost.querySelector("summary");
      if (summary instanceof HTMLElement) {
        summary.focus({ preventScroll: true });
      }
      event.preventDefault();
      event.stopPropagation();
    };

    const handleOutsideClick = (event: PointerEvent) => {
      const layers = resolveOpenDetailsLayers();
      if (layers.length === 0) {
        return;
      }
      const target = event.target as Node | null;
      if (!target) {
        return;
      }
      for (const layer of layers) {
        if (!layer.contains(target)) {
          layer.open = false;
        }
      }
    };

    document.addEventListener("keydown", handleEscapeDismiss, true);
    document.addEventListener("pointerdown", handleOutsideClick, true);
    return () => {
      document.removeEventListener("keydown", handleEscapeDismiss, true);
      document.removeEventListener("pointerdown", handleOutsideClick, true);
    };
  }, []);

  const globalNavLinks: NavLink[] = [...GLOBAL_NAV_LINKS];
  if (canViewApprovedModels) {
    globalNavLinks.push({ href: approvedModelsPath, label: "Approved models" });
  }
  if (hasPlatformRole) {
    globalNavLinks.push({ href: adminPath, label: "Admin" });
  }

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
  const showContextRegion =
    shellState === "Expanded" || (shellState === "Balanced" && !forceFocus);
  const shellTitle = currentProject?.name ?? resolveShellHeading(pathname);

  return (
    <div className="authenticatedShell" data-shell-state={shellState}>
      <a className="ukde-skip-link" href="#ukde-shell-work-region">
        Skip to work region
      </a>

      <header className="authenticatedShellHeader ukde-panel">
        <div className="authenticatedShellIdentity">
          <p className="authenticatedShellTitle">{shellTitle}</p>
          {currentProject ? (
            <p className="ukde-muted">Project workspace</p>
          ) : null}
        </div>

        <div className="authenticatedShellActions">
          <GlobalCommandBar
            currentProject={currentProject}
            pathname={pathname}
            projects={projects}
            session={session}
          />

          <ThemePreferenceControl className="workspaceThemeControl" />

          <Link className="workspaceHelpLink" href={healthPath}>
            Help
          </Link>

          <div className="workspaceBadges">
            <StatusChip tone={resolveEnvironmentTone()}>
              Env {resolveEnvironmentLabel()}
            </StatusChip>
            {currentProject ? (
              <StatusChip
                tone={
                  accessTierBadgeTones[currentProject.intendedAccessTier] ===
                  "success"
                    ? "success"
                    : accessTierBadgeTones[
                          currentProject.intendedAccessTier
                        ] === "warning"
                      ? "warning"
                      : "neutral"
                }
              >
                Tier {accessTierLabels[currentProject.intendedAccessTier]}
              </StatusChip>
            ) : (
              <StatusChip tone="warning">Tier CONTROLLED</StatusChip>
            )}
            <StatusChip tone="info">{shellState}</StatusChip>
          </div>

          <details className="workspaceMenu">
            <summary aria-label="User menu" className="workspaceMenuTrigger">
              {session.user.displayName}
            </summary>
            <div className="workspaceMenuPanel">
              <span className="ukde-muted">{session.user.email}</span>
              <span className="ukde-muted">
                {hasPlatformRole
                  ? session.user.platformRoles.join(", ")
                  : "No platform-role override"}
              </span>
              <Link href={activityPath}>My activity</Link>
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
                  const href = resolveProjectContextHref(
                    currentProject.id,
                    link.href
                  );
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
                    const href = resolveProjectContextHref(
                      currentProject.id,
                      link.href
                    );
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

          <div
            className="authenticatedShellWorkRegion"
            id="ukde-shell-work-region"
            ref={workRegionRef}
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
                <strong>{roleModeLabel}</strong>
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
