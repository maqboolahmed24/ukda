"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import type { SessionResponse, ShellState } from "@ukde/contracts";
import { DetailsDrawer, StatusChip } from "@ukde/ui/primitives";

import {
  type AdminSurfaceGroup,
  resolveAdminRoleMode,
  resolveAdminSurfaceGroups
} from "../lib/admin-console";
import {
  useAdaptiveSidePanelState,
  type SidePanelSection
} from "../lib/adaptive-side-panel";
import { adminPath } from "../lib/routes";

interface AdminConsoleShellProps {
  children: React.ReactNode;
  session: SessionResponse;
}

const GROUP_LABELS: Record<AdminSurfaceGroup, string> = {
  governance: "Governance",
  internal: "Internal",
  operations: "Operations",
  overview: "Overview"
};

function isActiveRoute(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

const SHELL_STATES: readonly ShellState[] = [
  "Expanded",
  "Balanced",
  "Compact",
  "Focus"
];

function isShellState(value: string | null): value is ShellState {
  return SHELL_STATES.includes(value as ShellState);
}

export function AdminConsoleShell({ children, session }: AdminConsoleShellProps) {
  const pathname = usePathname();
  const [shellState, setShellState] = useState<ShellState>("Expanded");
  const railDrawerReturnFocusRef = useRef<HTMLElement | null>(null);
  const railDrawerWasOpenRef = useRef(false);
  const roleMode = resolveAdminRoleMode(session);
  const groups = resolveAdminSurfaceGroups(session);
  const {
    closeDrawer: closeRailDrawer,
    drawerOpen: railDrawerOpen,
    openDrawer: openRailDrawer,
    panelSection: railPanelSection,
    setPanelSection: setRailPanelSection,
    showAside: showRailAside,
    showDrawerToggle: showRailDrawerToggle
  } = useAdaptiveSidePanelState({
    shellState,
    storageSurface: "admin-console-rail",
    initialSection: "context"
  });

  useEffect(() => {
    const shellElement = document.querySelector<HTMLElement>(".authenticatedShell");
    if (!shellElement) {
      return;
    }
    const syncShellState = () => {
      const raw = shellElement.getAttribute("data-shell-state");
      if (isShellState(raw)) {
        setShellState(raw);
      }
    };
    syncShellState();
    const observer = new MutationObserver(syncShellState);
    observer.observe(shellElement, {
      attributes: true,
      attributeFilter: ["data-shell-state"]
    });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (showRailAside) {
      closeRailDrawer();
    }
  }, [closeRailDrawer, showRailAside]);

  useEffect(() => {
    if (railDrawerWasOpenRef.current && !railDrawerOpen) {
      railDrawerReturnFocusRef.current?.focus({ preventScroll: true });
      railDrawerReturnFocusRef.current = null;
    }
    railDrawerWasOpenRef.current = railDrawerOpen;
  }, [railDrawerOpen]);

  const handleRailSectionChange = (nextSection: SidePanelSection) => {
    if (nextSection === railPanelSection) {
      return;
    }
    setRailPanelSection(nextSection);
  };
  const openAdminRailDrawer = (trigger: HTMLElement | null) => {
    railDrawerReturnFocusRef.current =
      trigger ??
      (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    openRailDrawer();
  };
  const railPanel = (
    <>
      <p className="ukde-eyebrow">Admin console</p>
      <h2>Platform governance</h2>
      <div className="adaptiveSidePanelTabs" role="tablist" aria-label="Admin rail sections">
        <button
          aria-selected={railPanelSection === "context"}
          className="secondaryButton"
          onClick={() => handleRailSectionChange("context")}
          role="tab"
          type="button"
        >
          Context
        </button>
        <button
          aria-selected={railPanelSection === "insights"}
          className="secondaryButton"
          onClick={() => handleRailSectionChange("insights")}
          role="tab"
          type="button"
        >
          Insights
        </button>
        <button
          aria-selected={railPanelSection === "actions"}
          className="secondaryButton"
          onClick={() => handleRailSectionChange("actions")}
          role="tab"
          type="button"
        >
          Actions
        </button>
      </div>
      {railPanelSection === "context" ? (
        <div className="adaptiveSidePanelBody">
          <div className="auditIntegrityRow">
            <StatusChip tone={roleMode.isAdmin ? "danger" : "info"}>
              {roleMode.label}
            </StatusChip>
            {!roleMode.isAdmin ? <StatusChip tone="warning">Read-only</StatusChip> : null}
          </div>
          <p className="ukde-muted">
            Platform routes remain separate from project-scoped activity and governance routes.
          </p>
          <nav aria-label="Admin console sections" className="adminConsoleNav">
            {groups.map((group) => (
              <section className="adminConsoleGroup" key={group.group}>
                <p className="ukde-eyebrow">{GROUP_LABELS[group.group]}</p>
                <ul>
                  {group.items.map((item) => {
                    const active = isActiveRoute(pathname, item.href);
                    return (
                      <li key={item.id}>
                        <Link
                          aria-current={active ? "page" : undefined}
                          className="adminConsoleLink"
                          href={item.href}
                        >
                          <span className="adminConsoleLinkHeading">
                            <span>{item.label}</span>
                            {item.readOnlyForAuditor && !roleMode.isAdmin ? (
                              <StatusChip tone="warning">Read-only</StatusChip>
                            ) : null}
                          </span>
                          <span className="ukde-muted">{item.description}</span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}
          </nav>
        </div>
      ) : railPanelSection === "insights" ? (
        <div className="adaptiveSidePanelBody">
          <ul className="projectMetaList">
            <li>
              <span>Shell state</span>
              <strong>{shellState}</strong>
            </li>
            <li>
              <span>Visible groups</span>
              <strong>{groups.length}</strong>
            </li>
            <li>
              <span>Total destinations</span>
              <strong>{groups.reduce((sum, group) => sum + group.items.length, 0)}</strong>
            </li>
          </ul>
        </div>
      ) : (
        <div className="adaptiveSidePanelBody">
          <div className="buttonRow">
            <Link className="secondaryButton" href={adminPath}>
              Admin overview
            </Link>
            {groups[0]?.items[0] ? (
              <Link className="secondaryButton" href={groups[0].items[0].href}>
                Open first surface
              </Link>
            ) : null}
          </div>
        </div>
      )}
    </>
  );

  return (
    <div className="adminConsoleFrame" data-shell-state={shellState}>
      {showRailAside ? <aside className="adminConsoleRail ukde-panel">{railPanel}</aside> : null}

      <div className="adminConsoleContent">
        {showRailDrawerToggle ? (
          <div className="adminConsoleDrawerToggleRow">
            <button
              className="secondaryButton"
              onClick={(event) => openAdminRailDrawer(event.currentTarget)}
              type="button"
            >
              {railDrawerOpen ? "Admin rail open" : "Open admin rail"}
            </button>
          </div>
        ) : null}
        {children}
      </div>

      <DetailsDrawer
        description="Admin console navigation drawer"
        open={railDrawerOpen}
        onClose={closeRailDrawer}
        title="Admin console"
      >
        <div className="adminConsoleDrawerPanel">{railPanel}</div>
      </DetailsDrawer>
    </div>
  );
}
