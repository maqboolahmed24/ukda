import { PageState, SkeletonLines } from "@ukde/ui/primitives";

interface RouteSkeletonProps {
  eyebrow?: string;
  title?: string;
  summary?: string;
  lines?: number;
}

export function RouteSkeleton({
  eyebrow = "Loading route",
  title = "Preparing workspace surface",
  summary = "Shell continuity is preserved while route content streams in.",
  lines = 3
}: RouteSkeletonProps) {
  return (
    <PageState
      className="routeSkeleton ukde-panel"
      description={summary}
      eyebrow={eyebrow}
      kind="loading"
      title={title}
    >
      <SkeletonLines lines={lines} />
    </PageState>
  );
}
