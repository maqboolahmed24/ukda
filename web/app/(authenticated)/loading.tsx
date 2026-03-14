import { RouteSkeleton } from "../../components/route-skeleton";
import { routeLoadingCopy } from "../../lib/route-state-copy";

export default function AuthenticatedRouteLoading() {
  return <RouteSkeleton {...routeLoadingCopy.authenticated} />;
}
