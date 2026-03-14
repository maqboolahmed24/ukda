import Link from "next/link";

import { PageState } from "@ukde/ui/primitives";

interface RouteNotFoundStateProps {
  title: string;
  summary: string;
  backHref: string;
  backLabel: string;
}

export function RouteNotFoundState({
  title,
  summary,
  backHref,
  backLabel
}: RouteNotFoundStateProps) {
  return (
    <main className="homeLayout">
      <PageState
        className="routeNotFoundState ukde-panel"
        description={summary}
        eyebrow="Not found"
        kind="not-found"
        title={title}
      >
        <div className="buttonRow">
          <Link className="secondaryButton" href={backHref}>
            {backLabel}
          </Link>
        </div>
      </PageState>
    </main>
  );
}
