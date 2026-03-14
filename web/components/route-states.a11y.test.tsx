// @vitest-environment jsdom

import {
  createElement,
  type AnchorHTMLAttributes,
  type ReactNode
} from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

interface MockLinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  children: ReactNode;
  href: string;
}

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: MockLinkProps) =>
    createElement("a", { ...props, href }, children)
}));

import { RouteErrorState } from "./route-error-state";
import { RouteNotFoundState } from "./route-not-found-state";
import { RouteSkeleton } from "./route-skeleton";

afterEach(() => {
  cleanup();
});

describe("route-level loading and error accessibility", () => {
  it("marks route skeleton as a loading status with aria-busy", () => {
    render(createElement(RouteSkeleton));

    const heading = screen.getByRole("heading", {
      name: "Preparing workspace surface"
    });
    const loadingSection = heading.closest("section");

    expect(loadingSection?.getAttribute("role")).toBe("status");
    expect(loadingSection?.getAttribute("aria-busy")).toBe("true");
    expect(screen.getByText(/shell continuity is preserved/i)).toBeTruthy();
  });

  it("uses safe route-error messaging and exposes retry controls", async () => {
    const user = userEvent.setup();
    const reset = vi.fn();

    render(
      createElement(RouteErrorState, {
        reset,
        summary: "The route could not be loaded.",
        title: "Route failed safely"
      })
    );

    expect(
      screen.getByText("Technical details stay in server logs and trace IDs.")
    ).toBeTruthy();
    const retry = screen.getByRole("button", { name: "Retry route" });
    await user.click(retry);
    expect(reset).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: "Back to projects" })).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Open safe error route" })
    ).toBeTruthy();
  });

  it("keeps not-found states actionable with a clear back path", () => {
    render(
      createElement(RouteNotFoundState, {
        backHref: "/projects",
        backLabel: "Back to projects",
        summary: "No project was found for this route.",
        title: "Project missing"
      })
    );

    expect(screen.getByRole("heading", { name: "Project missing" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to projects" })).toBeTruthy();
  });
});
