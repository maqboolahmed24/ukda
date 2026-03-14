// @vitest-environment jsdom

import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Drawer, MenuFlyout, ModalDialog, Toolbar } from "./primitives";

afterEach(() => {
  cleanup();
});

function ModalHarness() {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(true)} type="button">
        Open modal
      </button>
      <ModalDialog
        footer={
          <button type="button" onClick={() => undefined}>
            Confirm modal action
          </button>
        }
        onClose={() => setOpen(false)}
        open={open}
        title="Modal test"
      >
        <button type="button" onClick={() => undefined}>
          Secondary action
        </button>
      </ModalDialog>
    </div>
  );
}

function DrawerHarness() {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(true)} type="button">
        Open drawer
      </button>
      <Drawer onClose={() => setOpen(false)} open={open} title="Drawer test">
        <button type="button" onClick={() => undefined}>
          Drawer secondary action
        </button>
      </Drawer>
    </div>
  );
}

describe("primitives accessibility regression contract", () => {
  it("traps modal focus and returns focus to the trigger on close", async () => {
    const user = userEvent.setup();
    render(<ModalHarness />);

    const trigger = screen.getByRole("button", { name: "Open modal" });
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    await user.click(trigger);

    const closeButton = screen.getByRole("button", { name: "Close dialog" });
    const modalFooterAction = screen.getByRole("button", {
      name: "Confirm modal action"
    });

    await waitFor(() => {
      expect(document.activeElement).toBe(closeButton);
    });

    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(document.activeElement).toBe(modalFooterAction);

    await user.keyboard("{Tab}");
    expect(document.activeElement).toBe(closeButton);

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => {
      expect(document.activeElement).toBe(trigger);
    });
  });

  it("keeps drawer keyboard-safe and restores focus when dismissed", async () => {
    const user = userEvent.setup();
    render(<DrawerHarness />);

    const trigger = screen.getByRole("button", { name: "Open drawer" });
    await user.click(trigger);

    const closeButton = screen.getByRole("button", { name: "Close drawer" });
    await waitFor(() => {
      expect(document.activeElement).toBe(closeButton);
    });

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => {
      expect(document.activeElement).toBe(trigger);
    });
  });

  it("supports flyout keyboard navigation and escape focus return", async () => {
    const user = userEvent.setup();
    render(
      <MenuFlyout
        items={[
          { id: "alpha", label: "Alpha action" },
          { disabled: true, id: "bravo", label: "Bravo action" },
          { id: "charlie", label: "Charlie action" }
        ]}
        label="Open flyout"
      />
    );

    const trigger = screen.getByRole("button", { name: "Open flyout" });
    await user.click(trigger);

    const menu = screen.getByRole("menu");
    const alpha = within(menu).getByRole("menuitem", { name: "Alpha action" });
    const charlie = within(menu).getByRole("menuitem", {
      name: "Charlie action"
    });

    await waitFor(() => {
      expect(document.activeElement).toBe(alpha);
    });

    const controlsId = trigger.getAttribute("aria-controls");
    expect(controlsId).toBeTruthy();
    expect(menu.id).toBe(controlsId);

    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(charlie);

    await user.keyboard("{Home}");
    expect(document.activeElement).toBe(alpha);

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("applies toolbar roving focus for arrow/home/end keys", async () => {
    const user = userEvent.setup();
    const onZoomIn = vi.fn();
    const onFit = vi.fn();
    const onRotate = vi.fn();

    render(
      <Toolbar
        actions={[
          { id: "zoom-in", label: "Zoom in", onAction: onZoomIn },
          { disabled: true, id: "fit", label: "Fit width", onAction: onFit },
          { id: "rotate", label: "Rotate", onAction: onRotate }
        ]}
        label="Viewer commands"
      />
    );

    const toolbar = screen.getByRole("toolbar", { name: "Viewer commands" });
    const zoomIn = within(toolbar).getByRole("button", { name: "Zoom in" });
    const rotate = within(toolbar).getByRole("button", { name: "Rotate" });

    zoomIn.focus();
    expect(document.activeElement).toBe(zoomIn);

    await user.keyboard("{ArrowRight}");
    expect(document.activeElement).toBe(rotate);

    await user.keyboard("{Home}");
    expect(document.activeElement).toBe(zoomIn);

    await user.keyboard("{End}");
    expect(document.activeElement).toBe(rotate);
  });
});
