"use client";

import { useEffect, useState } from "react";

function resolveMediaPreference(query: string): string {
  if (
    typeof window === "undefined" ||
    typeof window.matchMedia !== "function"
  ) {
    return "unsupported";
  }
  try {
    const media = window.matchMedia(query);
    return media.matches ? "reduce" : "no-preference";
  } catch {
    return "unsupported";
  }
}

export function SecurityPreferencesCard() {
  const [reducedMotion, setReducedMotion] = useState("unresolved");
  const [reducedTransparency, setReducedTransparency] = useState("unresolved");

  useEffect(() => {
    setReducedMotion(
      resolveMediaPreference("(prefers-reduced-motion: reduce)")
    );
    setReducedTransparency(
      resolveMediaPreference("(prefers-reduced-transparency: reduce)")
    );
  }, []);

  return (
    <section className="sectionCard ukde-panel">
      <p className="ukde-eyebrow">Client diagnostics</p>
      <h2>Accessibility preference state</h2>
      <ul className="projectMetaList">
        <li>
          <span>Reduced motion</span>
          <strong>{reducedMotion}</strong>
        </li>
        <li>
          <span>Reduced transparency</span>
          <strong>{reducedTransparency}</strong>
        </li>
      </ul>
      <p className="ukde-muted">
        These values are browser-local diagnostics and do not mutate platform
        security settings.
      </p>
    </section>
  );
}
