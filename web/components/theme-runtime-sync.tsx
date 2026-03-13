"use client";

import { useEffect } from "react";

import {
  THEME_PREFERENCE_EVENT,
  THEME_PREFERENCE_STORAGE_KEY,
  readStoredThemePreference,
  subscribeThemeMediaChanges,
  syncThemeRuntime
} from "@ukde/ui";

export function ThemeRuntimeSync() {
  useEffect(() => {
    const sync = () => {
      syncThemeRuntime(readStoredThemePreference());
    };

    sync();
    const unsubscribeMedia = subscribeThemeMediaChanges(sync);

    const handleStorageChange = (event: StorageEvent) => {
      if (event.key && event.key !== THEME_PREFERENCE_STORAGE_KEY) {
        return;
      }
      sync();
    };

    const handlePreferenceEvent = () => {
      sync();
    };

    window.addEventListener("storage", handleStorageChange);
    window.addEventListener(THEME_PREFERENCE_EVENT, handlePreferenceEvent);

    return () => {
      unsubscribeMedia();
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener(THEME_PREFERENCE_EVENT, handlePreferenceEvent);
    };
  }, []);

  return null;
}
