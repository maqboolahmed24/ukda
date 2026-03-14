"use client";

import Link from "next/link";

import { PageState } from "@ukde/ui/primitives";

import { errorPath, projectsPath } from "../lib/routes";

interface RouteErrorStateProps {
  eyebrow?: string;
  reset?: () => void;
  title: string;
  summary: string;
  retryLabel?: string;
}

export function RouteErrorState({
  eyebrow = "Route boundary",
  reset,
  title,
  summary,
  retryLabel = "Retry route"
}: RouteErrorStateProps) {
  return (
    <main className="homeLayout">
      <PageState
        className="routeErrorState ukde-panel"
        description={summary}
        eyebrow={eyebrow}
        kind="error"
        title={title}
      >
        <p className="ukde-muted">
          Technical details stay in server logs and trace IDs.
        </p>
        <div className="buttonRow">
          {typeof reset === "function" ? (
            <button
              className="primaryButton"
              onClick={() => reset()}
              type="button"
            >
              {retryLabel}
            </button>
          ) : null}
          <Link className="secondaryButton" href={projectsPath}>
            Back to projects
          </Link>
          <Link className="secondaryButton" href={errorPath}>
            Open safe error route
          </Link>
        </div>
      </PageState>
    </main>
  );
}
