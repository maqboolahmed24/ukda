"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { SessionResponse } from "@ukde/contracts";
import { StatusChip } from "@ukde/ui/primitives";

import {
  type AdminSurfaceGroup,
  resolveAdminRoleMode,
  resolveAdminSurfaceGroups
} from "../lib/admin-console";

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

export function AdminConsoleShell({ children, session }: AdminConsoleShellProps) {
  const pathname = usePathname();
  const roleMode = resolveAdminRoleMode(session);
  const groups = resolveAdminSurfaceGroups(session);

  return (
    <div className="adminConsoleFrame">
      <aside className="adminConsoleRail ukde-panel">
        <p className="ukde-eyebrow">Admin console</p>
        <h2>Platform governance</h2>
        <div className="auditIntegrityRow">
          <StatusChip tone={roleMode.isAdmin ? "danger" : "info"}>
            {roleMode.label}
          </StatusChip>
          {!roleMode.isAdmin ? (
            <StatusChip tone="warning">Read-only</StatusChip>
          ) : null}
        </div>
        <p className="ukde-muted">
          Platform routes remain separate from project-scoped activity and
          governance routes.
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
      </aside>

      <div className="adminConsoleContent">{children}</div>
    </div>
  );
}
