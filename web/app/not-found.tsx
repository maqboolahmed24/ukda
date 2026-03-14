import { RouteNotFoundState } from "../components/route-not-found-state";
import { routeNotFoundCopy } from "../lib/route-state-copy";
import { rootPath } from "../lib/routes";

export default function RootNotFoundPage() {
  return (
    <RouteNotFoundState
      backHref={rootPath}
      backLabel="Return to entry"
      summary={routeNotFoundCopy.root.summary}
      title={routeNotFoundCopy.root.title}
    />
  );
}
