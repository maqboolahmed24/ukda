// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { ProjectSummary, SessionResponse } from "@ukde/contracts";

const routerPushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: routerPushMock
  })
}));

import { GlobalCommandBar } from "./global-command-bar";

afterEach(() => {
  cleanup();
  routerPushMock.mockReset();
});

const baseSession: SessionResponse = {
  session: {
    expiresAt: "2026-03-14T00:00:00Z",
    id: "session-1"
  },
  user: {
    displayName: "Lin",
    email: "lin@example.com",
    id: "user-1",
    platformRoles: [],
    sub: "oidc|lin"
  }
};

const projects: ProjectSummary[] = [
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
    name: "Archive one",
    purpose: "testing",
    status: "ACTIVE"
  },
  {
    baselinePolicySnapshotId: "baseline-2",
    canAccessSettings: false,
    canManageMembers: false,
    createdAt: "2026-03-13T09:00:00Z",
    createdBy: "user-1",
    currentUserRole: "RESEARCHER",
    id: "project-2",
    intendedAccessTier: "SAFEGUARDED",
    isMember: true,
    name: "Archive two",
    purpose: "testing",
    status: "ACTIVE"
  }
];

function renderBar(session: SessionResponse = baseSession) {
  return render(
    <GlobalCommandBar
      currentProject={projects[0]}
      pathname="/projects/project-1/documents/import"
      projects={projects}
      session={session}
    />
  );
}

describe("global command bar", () => {
  it("opens with Cmd/Ctrl+K and focuses command input", async () => {
    const user = userEvent.setup();
    renderBar();

    await user.keyboard("{Meta>}k{/Meta}");
    expect(
      await screen.findByRole("heading", { name: "Global command bar" })
    ).toBeTruthy();
    const input = screen.getByLabelText("Search commands");
    expect(document.activeElement).toBe(input);

    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("heading", { name: "Global command bar" })
    ).toBeNull();
  });

  it("returns focus to trigger on close and navigates selected command", async () => {
    const user = userEvent.setup();
    renderBar();

    const trigger = screen.getByRole("button", { name: /command bar/i });
    await user.click(trigger);
    await screen.findByRole("heading", { name: "Global command bar" });
    await user.type(screen.getByLabelText("Search commands"), "my activity");

    const listbox = screen.getByRole("listbox", { name: "Command results" });
    const option = within(listbox).getByRole("option", {
      name: /open my activity/i
    });
    await user.click(option);
    expect(routerPushMock).toHaveBeenCalledWith("/activity");

    await waitFor(() => {
      expect(
        screen.queryByRole("heading", { name: "Global command bar" })
      ).toBeNull();
    });
    expect(document.activeElement).toBe(trigger);
  });

  it("filters project-switcher mode and preserves nearest route section", async () => {
    const user = userEvent.setup();
    renderBar();

    await user.click(screen.getByRole("button", { name: "Project switcher" }));
    expect(
      await screen.findByRole("heading", { name: "Project switcher" })
    ).toBeTruthy();

    await user.type(screen.getByLabelText("Search commands"), "archive two");
    const listbox = screen.getByRole("listbox", { name: "Command results" });
    const option = within(listbox).getByRole("option", {
      name: /switch to archive two/i
    });

    await user.click(option);
    expect(routerPushMock).toHaveBeenCalledWith("/projects/project-2/documents/import");
  });

  it("does not expose admin-only commands for non-admin users", async () => {
    const user = userEvent.setup();
    renderBar();

    await user.click(screen.getByRole("button", { name: /command bar/i }));
    const input = screen.getByLabelText("Search commands");
    await user.type(input, "operations alerts");

    expect(screen.queryByRole("option", { name: /operations alerts/i })).toBeNull();
    expect(screen.getByText("No command results")).toBeTruthy();
  });

  it("exposes admin commands for admin users", async () => {
    const user = userEvent.setup();
    renderBar({
      ...baseSession,
      user: {
        ...baseSession.user,
        platformRoles: ["ADMIN"]
      }
    });

    await user.click(screen.getByRole("button", { name: /command bar/i }));
    const input = screen.getByLabelText("Search commands");
    await user.type(input, "operations alerts");

    expect(
      await screen.findByRole("option", { name: /open operations alerts/i })
    ).toBeTruthy();
  });
});
