import { RouteSkeleton } from "../../../../../components/route-skeleton";
import { routeLoadingCopy } from "../../../../../lib/route-state-copy";

export default function ProjectSearchLoading() {
  return <RouteSkeleton {...routeLoadingCopy.projectSearch} lines={4} />;
}
