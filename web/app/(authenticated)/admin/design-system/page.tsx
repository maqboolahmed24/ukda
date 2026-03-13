import { bootstrapShellStates } from "@ukde/contracts";
import {
  darkThemeColorTokens,
  designPillars,
  focusTokens,
  motionTokens,
  radiusTokens,
  shellStateNotes,
  spacingTokens,
  themeColorVariables,
  themePreferenceOptions,
  typographyTokens
} from "@ukde/ui";

import { DesignSystemDiagnostics } from "../../../../components/design-system-diagnostics";
import { DesignSystemPrimitivesShowcase } from "../../../../components/design-system-primitives-showcase";
import { PageHeader } from "../../../../components/page-header";
import { ThemePreferenceControl } from "../../../../components/theme-preference-control";

const COLOR_SWATCHES = [
  ["Canvas", darkThemeColorTokens.background.canvas],
  ["Frame", darkThemeColorTokens.background.frame],
  ["Surface", darkThemeColorTokens.surface.default],
  ["Surface raised", darkThemeColorTokens.surface.raised],
  ["Accent", darkThemeColorTokens.accent.primary],
  ["Success", darkThemeColorTokens.status.success],
  ["Warning", darkThemeColorTokens.status.warning],
  ["Danger", darkThemeColorTokens.status.danger],
  ["Focus ring", darkThemeColorTokens.focus.ring]
] as const;

const TYPE_EXAMPLES = [
  ["Shell title", "ukde-text-shell-title", "UKDataExtraction workspace shell"],
  ["Page title", "ukde-text-page-title", "Project governance overview"],
  [
    "Section title",
    "ukde-text-section-title",
    "Security and operations status"
  ],
  [
    "Body",
    "ukde-text-body",
    "Dense operational surfaces stay legible through strict spacing rhythm."
  ],
  ["Metadata", "ukde-text-meta", "REVIEW SURFACE · READ-ONLY"],
  ["Microcopy", "ukde-text-micro", "contrast: more | motion: reduce"]
] as const;

const SCALE_ENTRIES = Object.entries(spacingTokens);
const RADIUS_ENTRIES = Object.entries(radiusTokens);
const MOTION_ENTRIES = [
  ...Object.entries(motionTokens.duration),
  ...Object.entries(motionTokens.easing)
];

export default function DesignSystemPage() {
  return (
    <main className="homeLayout dsPage">
      <PageHeader
        eyebrow="Internal route"
        summary="Engineering validation surface for shared tokens, runtime theme behavior, focus language, and shell interaction posture."
        title="Obsidian web design-system gallery"
      />

      <section className="sectionCard ukde-panel dsSection">
        <div className="dsSectionControls">
          <ThemePreferenceControl />
          <span className="ukde-badge">Dark default</span>
          <span className="ukde-badge">Forced-colors safe</span>
          <span className="ukde-badge">Reduced-motion aware</span>
        </div>
      </section>

      <section className="ukde-grid" data-columns="2">
        <article className="sectionCard ukde-panel dsSection">
          <div className="sectionHeading">
            <p className="ukde-eyebrow">Runtime diagnostics</p>
            <h2>Browser preference and mode state</h2>
          </div>
          <DesignSystemDiagnostics />
          <p className="ukde-muted">
            Preference persistence key:
            <code className="statusDetail"> ukde.theme.preference</code>
          </p>
        </article>

        <article className="sectionCard ukde-panel dsSection">
          <div className="sectionHeading">
            <p className="ukde-eyebrow">Theme contract</p>
            <h2>Mode and variable map</h2>
          </div>
          <ul className="projectMetaList">
            <li>
              <span>Supported preferences</span>
              <strong>{themePreferenceOptions.join(", ")}</strong>
            </li>
            <li>
              <span>Dark variable count</span>
              <strong>{Object.keys(themeColorVariables.dark).length}</strong>
            </li>
            <li>
              <span>Light variable count</span>
              <strong>{Object.keys(themeColorVariables.light).length}</strong>
            </li>
            <li>
              <span>Focus ring width</span>
              <strong>{focusTokens.ringWidth}</strong>
            </li>
          </ul>
        </article>
      </section>

      <section className="sectionCard ukde-panel dsSection">
        <div className="sectionHeading">
          <p className="ukde-eyebrow">Semantic color tokens</p>
          <h2>Dark baseline swatches</h2>
        </div>
        <div className="dsTokenGrid">
          {COLOR_SWATCHES.map(([label, value]) => (
            <article className="dsTokenCard" key={label}>
              <span className="dsTokenSwatch" style={{ background: value }} />
              <strong>{label}</strong>
              <code>{value}</code>
            </article>
          ))}
        </div>
      </section>

      <section className="ukde-grid" data-columns="2">
        <article className="sectionCard ukde-panel dsSection">
          <div className="sectionHeading">
            <p className="ukde-eyebrow">Typography scale</p>
            <h2>Editorial and operational rhythm</h2>
          </div>
          <div className="dsTypeGrid">
            {TYPE_EXAMPLES.map(([label, className, sample]) => (
              <div className="dsTypeRow" key={label}>
                <p className="ukde-eyebrow">{label}</p>
                <p className={className}>{sample}</p>
              </div>
            ))}
          </div>
          <p className="ukde-muted">
            Families: {typographyTokens.family.sans.split(",")[0]} /{" "}
            {typographyTokens.family.serif.split(",")[0]} /{" "}
            {typographyTokens.family.mono.split(",")[0]}
          </p>
        </article>

        <article className="sectionCard ukde-panel dsSection">
          <div className="sectionHeading">
            <p className="ukde-eyebrow">Scale tokens</p>
            <h2>Spacing, radius, and motion</h2>
          </div>
          <div className="dsScaleColumns">
            <div>
              <p className="ukde-eyebrow">Spacing</p>
              <ul className="dsScaleList">
                {SCALE_ENTRIES.map(([step, value]) => (
                  <li key={`space-${step}`}>
                    <span>{step}</span>
                    <code>{value}</code>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="ukde-eyebrow">Radius</p>
              <ul className="dsScaleList">
                {RADIUS_ENTRIES.map(([token, value]) => (
                  <li key={`radius-${token}`}>
                    <span>{token}</span>
                    <code>{value}</code>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <p className="ukde-eyebrow">Motion tokens</p>
          <ul className="dsScaleList">
            {MOTION_ENTRIES.map(([token, value]) => (
              <li key={`motion-${token}`}>
                <span>{token}</span>
                <code>{value}</code>
              </li>
            ))}
          </ul>
        </article>
      </section>

      <section className="ukde-grid" data-columns="2">
        <article className="sectionCard ukde-panel dsSection">
          <div className="sectionHeading">
            <p className="ukde-eyebrow">Surface language</p>
            <h2>Quiet through overlay surfaces</h2>
          </div>
          <div className="dsSurfaceStack">
            <div className="ukde-panel ukde-surface-quiet dsSurfaceSample">
              Quiet surface
            </div>
            <div className="ukde-panel dsSurfaceSample">Default surface</div>
            <div className="ukde-panel ukde-surface-raised dsSurfaceSample">
              Raised surface
            </div>
            <div className="ukde-panel ukde-surface-overlay dsSurfaceSample">
              Overlay surface
            </div>
          </div>
        </article>

        <article className="sectionCard ukde-panel dsSection">
          <div className="sectionHeading">
            <p className="ukde-eyebrow">Interaction language</p>
            <h2>Focus, hover, selected, and disabled</h2>
          </div>
          <div className="dsInteractionGrid">
            <button
              className="ukde-button"
              data-variant="primary"
              type="button"
            >
              Primary action
            </button>
            <button
              className="ukde-button"
              data-state="selected"
              data-variant="secondary"
              type="button"
            >
              Selected state
            </button>
            <button
              className="ukde-button"
              data-variant="danger"
              disabled
              type="button"
            >
              Disabled danger
            </button>
            <input
              className="ukde-field"
              defaultValue="Focusable field"
              aria-label="Focusable field sample"
              readOnly
            />
          </div>
          <p className="ukde-muted">
            Tab through controls to verify visible focus rings on dark, light,
            and high-contrast render modes.
          </p>
        </article>
      </section>

      <section className="sectionCard ukde-panel dsSection">
        <div className="sectionHeading">
          <p className="ukde-eyebrow">Adaptive-state language</p>
          <h2>Expanded through Focus</h2>
        </div>
        <div className="ukde-grid" data-columns="2">
          {bootstrapShellStates.map((state) => (
            <article
              className="statCard ukde-panel ukde-surface-raised"
              key={state}
            >
              <h3>{state}</h3>
              <p className="ukde-muted">{shellStateNotes[state]}</p>
            </article>
          ))}
        </div>
        <ul className="stateList">
          {designPillars.map((pillar) => (
            <li key={pillar}>
              <strong>{pillar}</strong>
              <span>
                New primitives or route styles should inherit this behavior
                without page-local token forks.
              </span>
            </li>
          ))}
        </ul>
      </section>

      <DesignSystemPrimitivesShowcase />
    </main>
  );
}
