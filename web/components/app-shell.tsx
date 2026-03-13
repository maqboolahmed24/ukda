"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import type { SessionResponse, ShellState } from "@ukde/contracts";
import { resolveShellState } from "@ukde/contracts";
import { ThemePreferenceControl } from "./theme-preference-control";

const FOCUS_STORAGE_KEY = "ukde.shell.focus";

const NAV_LINKS = [
  { href: "/projects", label: "Project switcher" },
  { href: "/health", label: "Help" }
];

const SHELL_BRAND = "UKDATAEXTRACTION (UKDE)";

function resolveShellHeading(pathname: string): string {
  if (pathname.startsWith("/projects/")) {
    return "Project workspace";
  }
  if (pathname.startsWith("/projects")) {
    return "Projects";
  }
  if (pathname.startsWith("/activity")) {
    return "My activity";
  }
  if (pathname.startsWith("/admin/operations")) {
    return "Operations";
  }
  if (pathname.startsWith("/admin/audit")) {
    return "Audit";
  }
  if (pathname.startsWith("/admin/design-system")) {
    return "Design system";
  }
  if (pathname.startsWith("/health")) {
    return "System health";
  }
  if (pathname.startsWith("/logout")) {
    return "Sign out";
  }
  if (pathname.startsWith("/login")) {
    return "Secure access";
  }
  return "Secure workspace";
}

function isActiveRoute(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({
  children,
  session
}: {
  children: React.ReactNode;
  session?: SessionResponse | null;
}) {
  const pathname = usePathname();
  const [forceFocusMode, setForceFocusMode] = useState(false);
  const [shellState, setShellState] = useState<ShellState>("Expanded");

  useEffect(() => {
    const storedFocusMode = window.localStorage.getItem(FOCUS_STORAGE_KEY);
    if (storedFocusMode === "true") {
      setForceFocusMode(true);
    }
  }, []);

  useEffect(() => {
    const syncShellState = () => {
      setShellState(resolveShellState(window.innerWidth, forceFocusMode));
    };

    syncShellState();
    window.addEventListener("resize", syncShellState);
    return () => window.removeEventListener("resize", syncShellState);
  }, [forceFocusMode]);

  useEffect(() => {
    window.localStorage.setItem(FOCUS_STORAGE_KEY, String(forceFocusMode));
  }, [forceFocusMode]);

  const accountLabel = session?.user.displayName ?? "Access";
  const accountHref = session ? "/logout" : "/login";

  const navigationLinks = [
    ...NAV_LINKS,
    { href: accountHref, label: accountLabel }
  ];

  return (
    <div className="ukde-shell">
      <a className="ukde-skip-link" href="#ukde-page-host">
        Skip to content
      </a>
      <div className="ukde-frame">
        <div className="ukde-app-shell" data-shell-state={shellState}>
          <header className="ukde-app-header ukde-panel">
            <div className="ukde-shell-brand">
              <p className="ukde-eyebrow">{SHELL_BRAND}</p>
              <h1>{resolveShellHeading(pathname)}</h1>
            </div>
            <div className="ukde-shell-actions">
              <nav aria-label="Primary" className="ukde-shell-nav">
                {navigationLinks.map((link) => (
                  <Link
                    aria-current={
                      isActiveRoute(pathname, link.href) ? "page" : undefined
                    }
                    className="ukde-shell-link"
                    href={link.href}
                    key={link.href}
                  >
                    <span>{link.label}</span>
                  </Link>
                ))}
              </nav>
              <div className="ukde-shell-controls">
                <ThemePreferenceControl />
              </div>
              <div className="ukde-app-badges">
                <span className="ukde-badge">
                  Env {process.env.NEXT_PUBLIC_APP_ENV ?? "dev"}
                </span>
                <span className="ukde-badge">
                  Tier {process.env.NEXT_PUBLIC_ACCESS_TIER ?? "CONTROLLED"}
                </span>
              </div>
            </div>
          </header>
          <div className="ukde-app-content">
            <main className="ukde-page-host" id="ukde-page-host" tabIndex={-1}>
              {children}
            </main>
          </div>
        </div>
      </div>
    </div>
  );
}
