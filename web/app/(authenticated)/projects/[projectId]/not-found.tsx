import { RouteNotFoundState } from "../../../../components/route-not-found-state";
import { routeNotFoundCopy } from "../../../../lib/route-state-copy";
import { projectsPath } from "../../../../lib/routes";

export default function ProjectNotFoundPage() {
  return (
    <RouteNotFoundState
      backHref={projectsPath}
      backLabel="Back to projects"
      summary={routeNotFoundCopy.project.summary}
      title={routeNotFoundCopy.project.title}
    />
  );
}
