import { RouteSkeleton } from "../../../../../../components/route-skeleton";
import { routeLoadingCopy } from "../../../../../../lib/route-state-copy";

export default function ProjectEntityDetailLoading() {
  return <RouteSkeleton {...routeLoadingCopy.projectEntities} lines={5} />;
}
