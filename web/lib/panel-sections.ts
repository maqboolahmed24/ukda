export type SidePanelSection = "context" | "insights" | "actions";

const PANEL_SECTIONS: readonly SidePanelSection[] = [
  "context",
  "insights",
  "actions"
];

export interface NormalizedPanelSectionParam {
  value: SidePanelSection | undefined;
  canonicalValue: string | undefined;
  shouldRedirect: boolean;
}

export function isPanelSection(value: string): value is SidePanelSection {
  return PANEL_SECTIONS.includes(value as SidePanelSection);
}

export function normalizePanelSectionParam(
  raw: string | null | undefined
): NormalizedPanelSectionParam {
  if (typeof raw !== "string") {
    return {
      value: undefined,
      canonicalValue: undefined,
      shouldRedirect: false
    };
  }
  const normalized = raw.trim().toLowerCase();
  if (!isPanelSection(normalized)) {
    return {
      value: undefined,
      canonicalValue: undefined,
      shouldRedirect: true
    };
  }
  if (normalized === "context") {
    return {
      value: "context",
      canonicalValue: undefined,
      shouldRedirect: true
    };
  }
  return {
    value: normalized,
    canonicalValue: normalized,
    shouldRedirect: raw !== normalized
  };
}

export function resolvePanelSectionValue(
  raw: string | null | undefined,
  fallback: SidePanelSection = "context"
): SidePanelSection {
  const normalized = normalizePanelSectionParam(raw).value;
  return normalized ?? fallback;
}
