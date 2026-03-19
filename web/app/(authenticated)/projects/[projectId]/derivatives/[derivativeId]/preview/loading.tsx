import { RouteSkeleton } from "../../../../../../../components/route-skeleton";
import { routeLoadingCopy } from "../../../../../../../lib/route-state-copy";

export default function ProjectDerivativePreviewLoading() {
  return <RouteSkeleton {...routeLoadingCopy.projectDerivatives} lines={5} />;
}
