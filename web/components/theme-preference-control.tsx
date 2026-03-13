"use client";

import { useEffect, useId, useState } from "react";

import type { ThemePreference } from "@ukde/contracts";
import {
  THEME_PREFERENCE_EVENT,
  readStoredThemePreference,
  setStoredThemePreference,
  syncThemeRuntime,
  themePreferenceLabels,
  themePreferenceOptions
} from "@ukde/ui";

interface ThemePreferenceControlProps {
  className?: string;
  id?: string;
  label?: string;
}

export function ThemePreferenceControl({
  className,
  id,
  label = "Theme preference"
}: ThemePreferenceControlProps) {
  const generatedId = useId();
  const controlId = id ?? `ukde-theme-pref-${generatedId}`;
  const [preference, setPreference] = useState<ThemePreference>("system");

  useEffect(() => {
    const stored = readStoredThemePreference();
    setPreference(stored);
    syncThemeRuntime(stored);
  }, []);

  return (
    <div className={`ukde-theme-control ${className ?? ""}`.trim()}>
      <label className="ukde-visually-hidden" htmlFor={controlId}>
        {label}
      </label>
      <select
        className="ukde-select ukde-theme-select"
        id={controlId}
        onChange={(event) => {
          const nextPreference = event.target.value as ThemePreference;
          setPreference(nextPreference);
          setStoredThemePreference(nextPreference);
          syncThemeRuntime(nextPreference);
          window.dispatchEvent(new Event(THEME_PREFERENCE_EVENT));
        }}
        value={preference}
      >
        {themePreferenceOptions.map((option) => (
          <option key={option} value={option}>
            Theme {themePreferenceLabels[option]}
          </option>
        ))}
      </select>
    </div>
  );
}
