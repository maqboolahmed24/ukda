// @vitest-environment jsdom

import {
  createElement,
  type AnchorHTMLAttributes,
  type ReactNode
} from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { ProjectSummary, SessionResponse } from "@ukde/contracts";

const usePathnameMock = vi.fn<() => string>();
const useSearchParamsMock = vi.fn<() => URLSearchParams>();
const routerPushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
  useSearchParams: () => useSearchParamsMock(),
  useRouter: () => ({
    push: routerPushMock
  })
}));

interface MockLinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  children: ReactNode;
  href: string;
}

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: MockLinkProps) =>
    createElement("a", { ...props, href }, children)
}));

import { AuthenticatedShell } from "./authenticated-shell";
import { PageHeader } from "./page-header";

afterEach(() => {
  cleanup();
});

const SESSION: SessionResponse = {
  session: {
    expiresAt: "2026-03-14T00:00:00Z",
    id: "sess-1"
  },
  user: {
    displayName: "Alex Researcher",
    email: "alex@example.com",
    id: "user-1",
    platformRoles: ["ADMIN"],
    sub: "oidc|alex"
  }
};

const PROJECTS: ProjectSummary[] = [
  {
    baselinePolicySnapshotId: "baseline-1",
    canAccessSettings: true,
    canManageMembers: true,
    createdAt: "2026-03-13T09:00:00Z",
    createdBy: "user-1",
    currentUserRole: "PROJECT_LEAD",
    id: "project-1",
    intendedAccessTier: "CONTROLLED",
    isMember: true,
    name: "Aerial census archive",
    purpose: "Prompt 16 shell testing",
    status: "ACTIVE"
  }
];

function renderShell() {
  return render(
    createElement(AuthenticatedShell, {
      children: [
        createElement(PageHeader, {
          key: "header",
          overflowActions: [
            {
              href: "/projects/project-1/overview?view=history",
              label: "History"
            }
          ],
          primaryAction: {
            href: "/projects/project-1/documents/import",
            label: "Import documents"
          },
          secondaryActions: [
            {
              href: "/projects/project-1/documents",
              label: "Open documents"
            }
          ],
          summary:
            "Keyboard traversal should reach these actions from the shell.",
          title: "Project overview"
        }),
        createElement(
          "button",
          { key: "work-action", type: "button" },
          "Focusable work action"
        )
      ],
      csrfToken: "csrf-token",
      projects: PROJECTS,
      session: SESSION
    })
  );
}

async function tabUntil(
  user: ReturnType<typeof userEvent.setup>,
  target: HTMLElement,
  maxTabs = 40
): Promise<boolean> {
  for (let step = 0; step < maxTabs; step += 1) {
    if (document.activeElement === target) {
      return true;
    }
    await user.tab();
  }
  return document.activeElement === target;
}

describe("authenticated shell keyboard and focus contract", () => {
  beforeEach(() => {
    routerPushMock.mockReset();
    usePathnameMock.mockReturnValue("/projects/project-1/overview");
    useSearchParamsMock.mockReturnValue(new URLSearchParams());
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1366,
      writable: true
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 900,
      writable: true
    });
  });

  it("supports keyboard traversal from skip-link through nav and page-header actions", async () => {
    const user = userEvent.setup();
    renderShell();

    const skipLink = screen.getByRole("link", { name: "Skip to work region" });
    await user.tab();
    expect(document.activeElement).toBe(skipLink);

    const navLink = document.querySelector<HTMLElement>(
      ".authenticatedShellRail .authenticatedShellRailLink"
    );
    const primaryAction = screen.getByRole("link", {
      name: "Import documents"
    });

    expect(navLink).not.toBeNull();
    if (!navLink) {
      return;
    }

    const reachedNav = await tabUntil(user, navLink, 20);
    const reachedPrimaryAction = await tabUntil(user, primaryAction, 30);

    expect(reachedNav).toBe(true);
    expect(reachedPrimaryAction).toBe(true);
  });

  it("moves focus to the work region when route transitions come from shell chrome", async () => {
    const { rerender } = renderShell();
    const railLink = document.querySelector<HTMLElement>(
      ".authenticatedShellRail .authenticatedShellRailLink"
    );
    expect(railLink).not.toBeNull();
    if (!railLink) {
      return;
    }

    railLink.focus();
    expect(document.activeElement).toBe(railLink);

    usePathnameMock.mockReturnValue("/activity");
    rerender(
      createElement(AuthenticatedShell, {
        children: createElement(PageHeader, { title: "My activity" }),
        csrfToken: "csrf-token",
        projects: PROJECTS,
        session: SESSION
      })
    );

    await waitFor(() => {
      expect((document.activeElement as HTMLElement | null)?.id).toBe(
        "ukde-shell-work-region"
      );
    });
  });

  it("closes open shell details menus on Escape and restores focus to summary", async () => {
    const user = userEvent.setup();
    renderShell();

    const userMenuSummary = screen.getByLabelText("User menu");
    await user.click(userMenuSummary);

    const details = userMenuSummary.closest("details");
    expect(details?.open).toBe(true);

    await user.keyboard("{Escape}");

    expect(details?.open).toBe(false);
    expect(document.activeElement).toBe(userMenuSummary);
  });
});
