"use client";

import { useCallback, useEffect, useState } from "react";

import type { ThemeMode, ThemePreference } from "@ukde/contracts";
import {
  THEME_PREFERENCE_EVENT,
  readStoredThemePreference,
  setStoredThemePreference,
  subscribeThemeMediaChanges,
  syncThemeRuntime,
  themePreferenceLabels
} from "@ukde/ui";

interface ThemePreferenceControlProps {
  className?: string;
  id?: string;
  label?: string;
}

const THEME_PREFERENCE_CYCLE: Record<ThemePreference, ThemePreference> = {
  system: "dark",
  dark: "light",
  light: "system"
};

export function ThemePreferenceControl({
  className,
  id,
  label = "Theme preference"
}: ThemePreferenceControlProps) {
  const [preference, setPreference] = useState<ThemePreference>("system");
  const [resolvedMode, setResolvedMode] = useState<ThemeMode>("dark");

  const syncPreference = useCallback((nextPreference: ThemePreference) => {
    const runtime = syncThemeRuntime(nextPreference);
    setPreference(nextPreference);
    setResolvedMode(runtime.mode);
  }, []);

  useEffect(() => {
    const syncFromStorage = () => {
      syncPreference(readStoredThemePreference());
    };

    syncFromStorage();

    const handlePreferenceEvent = () => {
      syncFromStorage();
    };

    const unsubscribeMedia = subscribeThemeMediaChanges(() => {
      if (readStoredThemePreference() === "system") {
        syncFromStorage();
      }
    });

    window.addEventListener(THEME_PREFERENCE_EVENT, handlePreferenceEvent);

    return () => {
      unsubscribeMedia();
      window.removeEventListener(THEME_PREFERENCE_EVENT, handlePreferenceEvent);
    };
  }, [syncPreference]);

  const nextPreference = THEME_PREFERENCE_CYCLE[preference];
  const isSystem = preference === "system";
  const modeLabel = themePreferenceLabels[resolvedMode];
  const currentLabel = isSystem ? `System (${modeLabel})` : modeLabel;
  const nextLabel = themePreferenceLabels[nextPreference];

  return (
    <div
      className={`ukde-theme-control ${className ?? ""}`.trim()}
      data-theme-mode={resolvedMode}
      data-theme-preference={preference}
    >
      <button
        aria-label={`${label}: ${currentLabel}. Click to switch to ${nextLabel}.`}
        className="ukde-theme-toggle"
        id={id}
        onClick={() => {
          setStoredThemePreference(nextPreference);
          syncPreference(nextPreference);
          window.dispatchEvent(new Event(THEME_PREFERENCE_EVENT));
        }}
        title={`Theme ${currentLabel}`}
        type="button"
      >
        <span aria-hidden className="ukde-theme-bulb">
          <svg viewBox="0 0 24 24">
            <path d="M12 3a6 6 0 0 0-3.9 10.56c.89.81 1.45 1.9 1.58 3.09h4.63c.13-1.19.69-2.28 1.58-3.09A6 6 0 0 0 12 3Z" />
            <path d="M9.5 18h5" />
            <path d="M10.5 21h3" />
          </svg>
        </span>
        <span className="ukde-theme-state">
          {modeLabel}
        </span>
        <span aria-hidden className="ukde-theme-source">
          System
        </span>
      </button>
    </div>
  );
}
