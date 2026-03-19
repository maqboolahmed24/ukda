import { RouteSkeleton } from "../../../../../../components/route-skeleton";
import { routeLoadingCopy } from "../../../../../../lib/route-state-copy";

export default function ProjectDerivativeDetailLoading() {
  return <RouteSkeleton {...routeLoadingCopy.projectDerivatives} lines={5} />;
}
