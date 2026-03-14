"use client";

import { useEffect, useState } from "react";

import { SectionState } from "@ukde/ui/primitives";

import {
  COMMAND_BAR_OPEN_REQUEST_EVENT,
  COMMAND_BAR_STATE_EVENT,
  type CommandBarOpenRequestDetail,
  type CommandBarStateDetail
} from "../lib/command-events";

const INITIAL_STATE: CommandBarStateDetail = {
  activeCommandId: null,
  loading: false,
  mode: "command",
  open: false,
  query: "",
  resultCount: 0
};

function requestCommandBarOpen(detail: CommandBarOpenRequestDetail): void {
  window.dispatchEvent(
    new CustomEvent<CommandBarOpenRequestDetail>(
      COMMAND_BAR_OPEN_REQUEST_EVENT,
      {
        detail
      }
    )
  );
}

export function DesignSystemCommandDiagnostics() {
  const [state, setState] = useState<CommandBarStateDetail>(INITIAL_STATE);

  useEffect(() => {
    const handleState = (event: Event) => {
      if (!(event instanceof CustomEvent)) {
        return;
      }
      setState(event.detail as CommandBarStateDetail);
    };

    window.addEventListener(COMMAND_BAR_STATE_EVENT, handleState as EventListener);
    return () => {
      window.removeEventListener(
        COMMAND_BAR_STATE_EVENT,
        handleState as EventListener
      );
    };
  }, []);

  return (
    <section className="sectionCard ukde-panel dsSection">
      <div className="sectionHeading">
        <p className="ukde-eyebrow">Command diagnostics</p>
        <h2>Global command bar and project switcher state</h2>
      </div>

      <div className="buttonRow">
        <button
          className="secondaryButton"
          onClick={() => requestCommandBarOpen({ mode: "command" })}
          type="button"
        >
          Open command bar
        </button>
        <button
          className="secondaryButton"
          onClick={() => requestCommandBarOpen({ mode: "project-switcher" })}
          type="button"
        >
          Open project switcher
        </button>
        <button
          className="secondaryButton"
          onClick={() =>
            requestCommandBarOpen({
              mode: "command",
              query: "zzzzzz"
            })
          }
          type="button"
        >
          Open no-results state
        </button>
      </div>

      <ul className="projectMetaList">
        <li>
          <span>Open</span>
          <strong>{state.open ? "yes" : "no"}</strong>
        </li>
        <li>
          <span>Mode</span>
          <strong>{state.mode}</strong>
        </li>
        <li>
          <span>Result count</span>
          <strong>{state.resultCount}</strong>
        </li>
        <li>
          <span>Loading</span>
          <strong>{state.loading ? "yes" : "no"}</strong>
        </li>
        <li>
          <span>Active command</span>
          <strong>{state.activeCommandId ?? "none"}</strong>
        </li>
      </ul>

      <SectionState
        description="Verify Cmd/Ctrl+K open/close behavior, input focus on open, Arrow/Home/End traversal, Enter execution, Escape close, and safe focus return."
        title="Keyboard traversal checklist"
      />

      <SectionState
        description="Verify role-aware command visibility and project-switch preservation from overview/documents/jobs/activity/settings routes."
        title="Scope and role checklist"
      />
    </section>
  );
}
