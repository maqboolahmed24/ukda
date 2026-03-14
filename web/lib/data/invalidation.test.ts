import { beforeEach, describe, expect, it, vi } from "vitest";

const revalidatePathMock = vi.fn();

vi.mock("next/cache", () => ({
  revalidatePath: (...args: unknown[]) => revalidatePathMock(...args)
}));

import { revalidateAfterMutation } from "./invalidation";

describe("mutation invalidation", () => {
  beforeEach(() => {
    revalidatePathMock.mockReset();
  });

  it("revalidates all configured paths for successful project creation", () => {
    revalidateAfterMutation("projects.create", {
      createdProjectId: "project-1"
    });

    expect(revalidatePathMock).toHaveBeenCalledWith("/projects");
    expect(revalidatePathMock).toHaveBeenCalledWith(
      "/projects/project-1/overview"
    );
    expect(revalidatePathMock).toHaveBeenCalledWith(
      "/projects/project-1/settings"
    );
    expect(revalidatePathMock).toHaveBeenCalledWith("/projects/project-1/jobs");
  });

  it("deduplicates repeated path targets", () => {
    revalidateAfterMutation("auth.login");
    const unique = new Set(
      revalidatePathMock.mock.calls.map(([path]) => String(path))
    );
    expect(unique.size).toBe(revalidatePathMock.mock.calls.length);
  });
});

