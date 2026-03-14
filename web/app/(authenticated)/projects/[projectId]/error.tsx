"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { PageState } from "@ukde/ui/primitives";

import { routeErrorCopy } from "../../../../lib/route-state-copy";
import { projectOverviewPath } from "../../../../lib/routes";

export default function ProjectRouteError({
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const params = useParams<{ projectId: string }>();
  const projectId = params?.projectId ?? "";
  const copy = routeErrorCopy.project;

  return (
    <main className="homeLayout">
      <PageState
        className="routeErrorState ukde-panel"
        description={copy.summary}
        eyebrow={copy.eyebrow}
        kind="error"
        title={copy.title}
      >
        <p className="ukde-muted">
          Technical details are intentionally withheld from browser output.
        </p>
        <div className="buttonRow">
          <button
            className="primaryButton"
            onClick={() => reset()}
            type="button"
          >
            {copy.retryLabel ?? "Retry route"}
          </button>
          {projectId ? (
            <Link
              className="secondaryButton"
              href={projectOverviewPath(projectId)}
            >
              Project overview
            </Link>
          ) : null}
        </div>
      </PageState>
    </main>
  );
}
