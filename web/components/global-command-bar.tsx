"use client";

import { startTransition, useDeferredValue, useEffect, useId, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type { ProjectSummary, SessionResponse } from "@ukde/contracts";
import { ModalDialog, SectionState } from "@ukde/ui/primitives";

import {
  COMMAND_BAR_OPEN_REQUEST_EVENT,
  COMMAND_BAR_STATE_EVENT,
  type CommandBarMode,
  type CommandBarOpenRequestDetail,
  type CommandBarStateDetail
} from "../lib/command-events";
import {
  buildCommandRegistry,
  filterCommands,
  groupCommands,
  type CommandDefinition
} from "../lib/command-registry";

interface GlobalCommandBarProps {
  currentProject: ProjectSummary | null;
  pathname: string;
  projects: ProjectSummary[];
  session: SessionResponse;
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  if (target.isContentEditable) {
    return true;
  }
  return (
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT"
  );
}

function modeTitle(mode: CommandBarMode): string {
  return mode === "project-switcher"
    ? "Project switcher"
    : "Global command bar";
}

function modeDescription(mode: CommandBarMode): string {
  if (mode === "project-switcher") {
    return "Switch projects quickly while preserving the nearest matching workspace section when safe.";
  }
  return "Navigate routes and trigger safe high-frequency actions with keyboard-first controls.";
}

function modePlaceholder(mode: CommandBarMode): string {
  return mode === "project-switcher"
    ? "Filter projects by name, role, or tier"
    : "Type a route, action, or keyword";
}

function dispatchCommandBarState(detail: CommandBarStateDetail): void {
  window.dispatchEvent(
    new CustomEvent<CommandBarStateDetail>(COMMAND_BAR_STATE_EVENT, { detail })
  );
}

export function GlobalCommandBar({
  currentProject,
  pathname,
  projects,
  session
}: GlobalCommandBarProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<CommandBarMode>("command");
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputId = useId();
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const commandTriggerRef = useRef<HTMLButtonElement | null>(null);
  const projectSwitcherTriggerRef = useRef<HTMLButtonElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  const allCommands = useMemo(
    () =>
      buildCommandRegistry({
        currentProject,
        pathname,
        projects,
        session
      }),
    [currentProject, pathname, projects, session]
  );

  const modeScopedCommands = useMemo(() => {
    if (mode === "project-switcher") {
      return allCommands.filter((command) => command.group === "Projects");
    }
    return allCommands;
  }, [allCommands, mode]);

  const deferredQuery = useDeferredValue(query);
  const loading = open && query !== deferredQuery;

  const filteredCommands = useMemo(
    () => filterCommands(modeScopedCommands, deferredQuery),
    [deferredQuery, modeScopedCommands]
  );

  const groupedCommands = useMemo(
    () => groupCommands(filteredCommands),
    [filteredCommands]
  );

  useEffect(() => {
    setActiveIndex(0);
  }, [deferredQuery, mode, open]);

  useEffect(() => {
    if (filteredCommands.length === 0) {
      setActiveIndex(0);
      return;
    }
    setActiveIndex((current) =>
      Math.min(Math.max(current, 0), filteredCommands.length - 1)
    );
  }, [filteredCommands.length]);

  useEffect(() => {
    const activeCommand = filteredCommands[activeIndex] ?? null;
    dispatchCommandBarState({
      activeCommandId: activeCommand?.id ?? null,
      loading,
      mode,
      open,
      query,
      resultCount: filteredCommands.length
    });
  }, [activeIndex, filteredCommands, loading, mode, open, query]);

  const openCommandBar = (
    nextMode: CommandBarMode,
    nextQuery = "",
    trigger?: HTMLElement | null
  ) => {
    returnFocusRef.current =
      trigger ??
      (document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null);
    setMode(nextMode);
    setQuery(nextQuery);
    setOpen(true);
  };

  useEffect(() => {
    const handleOpenRequest = (event: Event) => {
      const detail =
        event instanceof CustomEvent
          ? (event.detail as CommandBarOpenRequestDetail | undefined)
          : undefined;
      openCommandBar(detail?.mode ?? "command", detail?.query ?? "");
    };

    window.addEventListener(
      COMMAND_BAR_OPEN_REQUEST_EVENT,
      handleOpenRequest as EventListener
    );
    return () => {
      window.removeEventListener(
        COMMAND_BAR_OPEN_REQUEST_EVENT,
        handleOpenRequest as EventListener
      );
    };
  }, []);

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if (event.defaultPrevented) {
        return;
      }
      if (event.key.toLowerCase() !== "k") {
        return;
      }
      if (!(event.metaKey || event.ctrlKey) || event.altKey) {
        return;
      }
      if (isEditableTarget(event.target)) {
        event.preventDefault();
        openCommandBar(
          "command",
          "",
          event.target instanceof HTMLElement ? event.target : null
        );
        return;
      }
      event.preventDefault();
      openCommandBar(
        "command",
        "",
        event.target instanceof HTMLElement ? event.target : null
      );
    };

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  const closeCommandBar = () => {
    setOpen(false);
    setQuery("");
    setMode("command");
  };

  const executeCommand = (command: CommandDefinition) => {
    closeCommandBar();
    router.push(command.href);
  };

  const focusOption = (index: number) => {
    if (filteredCommands.length === 0) {
      return;
    }
    const safeIndex = Math.min(
      Math.max(index, 0),
      Math.max(filteredCommands.length - 1, 0)
    );
    setActiveIndex(safeIndex);
    optionRefs.current[safeIndex]?.focus({ preventScroll: true });
  };

  const commandBarControlsId = "ukde-command-controls";

  return (
    <>
      <div
        aria-label="Global command controls"
        className="globalCommandControls"
        id={commandBarControlsId}
        role="group"
      >
        <button
          className="workspaceMenuTrigger"
          onClick={(event) =>
            openCommandBar("project-switcher", "", event.currentTarget)
          }
          ref={projectSwitcherTriggerRef}
          type="button"
        >
          Project switcher
        </button>
        <button
          aria-keyshortcuts="Meta+K Control+K"
          className="workspaceMenuTrigger globalCommandTrigger"
          onClick={(event) => openCommandBar("command", "", event.currentTarget)}
          ref={commandTriggerRef}
          type="button"
        >
          <span>Command bar</span>
          <span aria-hidden className="ukde-kbd">
            ⌘/Ctrl + K
          </span>
        </button>
      </div>

      <ModalDialog
        className="globalCommandDialog"
        closeLabel="Close command bar"
        description={modeDescription(mode)}
        onClose={closeCommandBar}
        open={open}
        returnFocusRef={returnFocusRef}
        title={modeTitle(mode)}
      >
        <div className="globalCommandBody">
          <label className="ukde-visually-hidden" htmlFor={inputId}>
            Search commands
          </label>
          <input
            autoFocus
            className="ukde-field globalCommandInput"
            data-ukde-initial-focus="true"
            id={inputId}
            onChange={(event) => {
              const nextValue = event.target.value;
              startTransition(() => {
                setQuery(nextValue);
              });
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                closeCommandBar();
                return;
              }
              if (event.key === "ArrowDown") {
                event.preventDefault();
                focusOption(activeIndex);
                return;
              }
              if (event.key === "Enter" && filteredCommands[activeIndex]) {
                event.preventDefault();
                executeCommand(filteredCommands[activeIndex]);
              }
            }}
            placeholder={modePlaceholder(mode)}
            value={query}
          />

          {loading ? (
            <SectionState
              description="Filtering commands for the current role and route context."
              kind="loading"
              title="Updating command results"
            />
          ) : filteredCommands.length === 0 ? (
            <SectionState
              description={
                mode === "project-switcher"
                  ? "No project matched this filter. Clear the query to see all accessible projects."
                  : "No command matched this query. Try route names, section labels, or role keywords."
              }
              kind="no-results"
              title="No command results"
            />
          ) : (
            <div
              aria-label="Command results"
              className="globalCommandResults"
              role="listbox"
            >
              {groupedCommands.map((group) => (
                <section className="globalCommandGroup" key={group.group}>
                  <p className="ukde-eyebrow">{group.group}</p>
                  <ul>
                    {group.items.map((command) => {
                      const optionIndex = filteredCommands.findIndex(
                        (candidate) => candidate.id === command.id
                      );
                      const selected = optionIndex === activeIndex;
                      return (
                        <li key={command.id}>
                          <button
                            aria-selected={selected}
                            className="globalCommandOption"
                            data-selected={selected ? "yes" : "no"}
                            onClick={() => executeCommand(command)}
                            onFocus={() => setActiveIndex(optionIndex)}
                            onKeyDown={(event) => {
                              if (event.key === "ArrowDown") {
                                event.preventDefault();
                                focusOption(optionIndex + 1);
                                return;
                              }
                              if (event.key === "ArrowUp") {
                                event.preventDefault();
                                focusOption(optionIndex - 1);
                                return;
                              }
                              if (event.key === "Home") {
                                event.preventDefault();
                                focusOption(0);
                                return;
                              }
                              if (event.key === "End") {
                                event.preventDefault();
                                focusOption(filteredCommands.length - 1);
                                return;
                              }
                              if (event.key === "Escape") {
                                event.preventDefault();
                                closeCommandBar();
                                return;
                              }
                              if (
                                event.key === "Enter" ||
                                event.key === " "
                              ) {
                                event.preventDefault();
                                executeCommand(command);
                              }
                            }}
                            ref={(element) => {
                              optionRefs.current[optionIndex] = element;
                            }}
                            role="option"
                            tabIndex={selected ? 0 : -1}
                            type="button"
                          >
                            <span className="globalCommandLabel">
                              {command.label}
                            </span>
                            <span className="globalCommandMeta">
                              {command.scope}
                              {command.description ? ` · ${command.description}` : ""}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </div>
      </ModalDialog>
    </>
  );
}
