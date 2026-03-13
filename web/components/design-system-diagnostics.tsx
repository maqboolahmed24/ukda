"use client";

import { useEffect, useState } from "react";

import { resolveAdaptiveShellState } from "@ukde/contracts";
import {
  THEME_PREFERENCE_EVENT,
  readStoredThemePreference,
  readThemeMediaState,
  resolveThemeRuntime,
  subscribeThemeMediaChanges,
  type ThemeRuntimeState
} from "@ukde/ui";

function resolveRuntimeState(): ThemeRuntimeState {
  const preference = readStoredThemePreference();
  return resolveThemeRuntime(preference, readThemeMediaState());
}

export function DesignSystemDiagnostics() {
  const [runtimeState, setRuntimeState] = useState<ThemeRuntimeState | null>(
    null
  );
  const [shellSnapshot, setShellSnapshot] = useState<{
    width: number;
    height: number;
    state: string;
  } | null>(null);

  useEffect(() => {
    const sync = () => {
      setRuntimeState(resolveRuntimeState());
      setShellSnapshot({
        width: window.innerWidth,
        height: window.innerHeight,
        state: resolveAdaptiveShellState({
          viewportWidth: window.innerWidth,
          viewportHeight: window.innerHeight,
          taskContext: "standard"
        })
      });
    };

    sync();
    const unsubscribeMedia = subscribeThemeMediaChanges(sync);
    window.addEventListener("resize", sync);

    const handlePreferenceChange = () => {
      sync();
    };

    window.addEventListener(THEME_PREFERENCE_EVENT, handlePreferenceChange);

    return () => {
      unsubscribeMedia();
      window.removeEventListener("resize", sync);
      window.removeEventListener(
        THEME_PREFERENCE_EVENT,
        handlePreferenceChange
      );
    };
  }, []);

  if (!runtimeState) {
    return (
      <p className="ukde-muted">
        Theme diagnostics initialize after browser preference checks complete.
      </p>
    );
  }

  return (
    <ul className="projectMetaList" aria-live="polite">
      <li>
        <span>Stored preference</span>
        <strong>{runtimeState.preference}</strong>
      </li>
      <li>
        <span>Resolved mode</span>
        <strong>{runtimeState.mode}</strong>
      </li>
      <li>
        <span>Contrast posture</span>
        <strong>{runtimeState.contrast}</strong>
      </li>
      <li>
        <span>Forced colors</span>
        <strong>
          {runtimeState.forcedColorsActive ? "active" : "inactive"}
        </strong>
      </li>
      <li>
        <span>Reduced motion</span>
        <strong>{runtimeState.motion}</strong>
      </li>
      <li>
        <span>Reduced transparency</span>
        <strong>{runtimeState.reducedTransparency}</strong>
      </li>
      {shellSnapshot ? (
        <>
          <li>
            <span>Viewport</span>
            <strong>
              {shellSnapshot.width}×{shellSnapshot.height}
            </strong>
          </li>
          <li>
            <span>Adaptive shell state</span>
            <strong>{shellSnapshot.state}</strong>
          </li>
        </>
      ) : null}
    </ul>
  );
}
