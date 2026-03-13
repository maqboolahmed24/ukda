"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface ProjectSideNavProps {
  projectId: string;
  canAccessMemberWorkspace: boolean;
  canAccessSettings: boolean;
}

interface NavItem {
  href: string;
  label: string;
  requiresMembership?: boolean;
  requiresSettings?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "overview", label: "Overview", requiresMembership: true },
  { href: "documents", label: "Documents", requiresMembership: true },
  { href: "jobs", label: "Jobs", requiresMembership: true },
  {
    href: "export-candidates",
    label: "Export candidates",
    requiresMembership: true
  },
  {
    href: "export-requests",
    label: "Export requests",
    requiresMembership: true
  },
  { href: "export-review", label: "Export review", requiresMembership: true },
  { href: "activity", label: "Activity", requiresMembership: true },
  { href: "settings", label: "Settings", requiresSettings: true }
];

export function ProjectSideNav({
  projectId,
  canAccessMemberWorkspace,
  canAccessSettings
}: ProjectSideNavProps) {
  const pathname = usePathname();
  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.requiresMembership && !canAccessMemberWorkspace) {
      return false;
    }
    if (item.requiresSettings && !canAccessSettings) {
      return false;
    }
    return true;
  });

  return (
    <nav aria-label="Project navigation" className="projectSideNav ukde-panel">
      <p className="ukde-eyebrow">Project navigation</p>
      <ul>
        {visibleItems.map((item) => {
          const href = `/projects/${projectId}/${item.href}`;
          return (
            <li key={item.href}>
              <Link
                aria-current={pathname === href ? "page" : undefined}
                href={href}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
