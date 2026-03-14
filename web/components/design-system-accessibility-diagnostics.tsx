"use client";

import { useEffect, useState } from "react";

import { SectionState } from "@ukde/ui/primitives";

interface AccessibilityRuntimeSnapshot {
  contrast: string;
  forcedColors: string;
  motion: string;
  transparency: string;
}

function readSnapshot(): AccessibilityRuntimeSnapshot {
  const root = document.documentElement.dataset;
  return {
    contrast: root.themeContrast ?? "unknown",
    forcedColors: root.themeForcedColors ?? "unknown",
    motion: root.themeMotion ?? "unknown",
    transparency: root.themeTransparency ?? "unknown"
  };
}

export function DesignSystemAccessibilityDiagnostics() {
  const [snapshot, setSnapshot] = useState<AccessibilityRuntimeSnapshot | null>(
    null
  );

  useEffect(() => {
    const sync = () => {
      setSnapshot(readSnapshot());
    };
    sync();
    window.addEventListener("resize", sync);
    window.addEventListener("ukde-theme-preference-change", sync);
    return () => {
      window.removeEventListener("resize", sync);
      window.removeEventListener("ukde-theme-preference-change", sync);
    };
  }, []);

  return (
    <section className="sectionCard ukde-panel dsSection">
      <div className="sectionHeading">
        <p className="ukde-eyebrow">Accessibility diagnostics</p>
        <h2>Keyboard, focus, motion, and contrast checks</h2>
      </div>

      <ul className="projectMetaList">
        <li>
          <span>Contrast posture</span>
          <strong>{snapshot?.contrast ?? "initializing"}</strong>
        </li>
        <li>
          <span>Forced colors</span>
          <strong>{snapshot?.forcedColors ?? "initializing"}</strong>
        </li>
        <li>
          <span>Reduced motion</span>
          <strong>{snapshot?.motion ?? "initializing"}</strong>
        </li>
        <li>
          <span>Reduced transparency</span>
          <strong>{snapshot?.transparency ?? "initializing"}</strong>
        </li>
      </ul>

      <SectionState
        title="Keyboard traversal checklist"
        description="Use Tab from skip link through nav rail, context bar, page header actions, and work region. Use Escape to close open flyouts, dialogs, and drawers."
      />

      <SectionState
        title="Overlay and toolbar checklist"
        description="Toolbar uses arrow-key roving focus. Flyout menus support ArrowUp/ArrowDown + Escape. Dialog and drawer trap Tab and restore focus on close."
      />

      <SectionState
        title="High-contrast and reduced-motion checklist"
        description="Focus rings, selected states, badges, and status chips must remain visible in forced-colors. Non-essential motion/transparency should be reduced when preferences request it."
      />
    </section>
  );
}
