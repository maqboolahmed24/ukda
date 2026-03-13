import { bootstrapShellStates } from "@ukde/contracts";
import {
  designPillars,
  shellStateNotes,
  themePreferenceOptions,
  themeTokens
} from "@ukde/ui";

export default function DesignSystemPage() {
  return (
    <main className="homeLayout">
      <section className="sectionCard ukde-panel">
        <div className="sectionHeading">
          <p className="ukde-eyebrow">Internal route</p>
          <h1>Design-system foundation gallery.</h1>
        </div>
        <p className="ukde-muted">
          This surface is role-gated and used to verify shared tokens, shell
          behaviors, and keyboard-safe primitives before phase-specific UI
          ships.
        </p>
        <div className="ukde-toolbar" aria-label="Toolbar sample">
          <button className="ukde-shell-button" type="button">
            Primary command
          </button>
          <button className="ukde-shell-button" type="button">
            Secondary command
          </button>
          <button className="ukde-shell-button" type="button">
            Overflow
          </button>
        </div>
      </section>

      <section className="ukde-grid" data-columns="2">
        <article className="sectionCard ukde-panel">
          <div className="sectionHeading">
            <p className="ukde-eyebrow">Tokens</p>
            <h2>Theme bootstrap</h2>
          </div>
          <ul className="stateList">
            <li>
              <strong>Background</strong>
              <span>{themeTokens.colors.background}</span>
            </li>
            <li>
              <strong>Surface</strong>
              <span>{themeTokens.colors.surfaceStrong}</span>
            </li>
            <li>
              <strong>Accent</strong>
              <span>{themeTokens.colors.accent}</span>
            </li>
            <li>
              <strong>Focus</strong>
              <span>{themeTokens.colors.focus}</span>
            </li>
            <li>
              <strong>Motion</strong>
              <span>{themeTokens.motion.quick}</span>
            </li>
          </ul>
        </article>

        <article className="sectionCard ukde-panel">
          <div className="sectionHeading">
            <p className="ukde-eyebrow">Pillars</p>
            <h2>Design expectations</h2>
          </div>
          <ul className="stateList">
            {designPillars.map((pillar) => (
              <li key={pillar}>
                <strong>{pillar}</strong>
                <span>
                  Shared primitives should make this the default, not a
                  page-local exception.
                </span>
              </li>
            ))}
          </ul>
        </article>
      </section>

      <section className="sectionCard ukde-panel">
        <div className="sectionHeading">
          <p className="ukde-eyebrow">Adaptive shell states</p>
          <h2>Expanded through Focus</h2>
        </div>
        <div className="ukde-grid" data-columns="2">
          {bootstrapShellStates.map((state) => (
            <article className="statCard ukde-panel ukde-stat" key={state}>
              <h3>{state}</h3>
              <p className="ukde-muted">{shellStateNotes[state]}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="sectionCard ukde-panel">
        <div className="sectionHeading">
          <p className="ukde-eyebrow">Theme controls</p>
          <h2>Supported preference modes</h2>
        </div>
        <ul className="stateList">
          {themePreferenceOptions.map((option) => (
            <li key={option}>
              <strong>{option}</strong>
              <span>
                The shell persists this choice in local storage and syncs
                browser preference changes when set to system.
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
