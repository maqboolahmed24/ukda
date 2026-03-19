import { RouteSkeleton } from "../../../../../components/route-skeleton";
import { routeLoadingCopy } from "../../../../../lib/route-state-copy";

export default function ProjectDerivativesLoading() {
  return <RouteSkeleton {...routeLoadingCopy.projectDerivatives} lines={4} />;
}
