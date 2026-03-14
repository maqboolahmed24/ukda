import { RouteNotFoundState } from "../../../components/route-not-found-state";
import { routeNotFoundCopy } from "../../../lib/route-state-copy";
import { adminPath } from "../../../lib/routes";

export default function AdminNotFoundPage() {
  return (
    <RouteNotFoundState
      backHref={adminPath}
      backLabel="Back to admin"
      summary={routeNotFoundCopy.admin.summary}
      title={routeNotFoundCopy.admin.title}
    />
  );
}
