import { RouteSkeleton } from "../../../../../../../components/route-skeleton";
import { routeLoadingCopy } from "../../../../../../../lib/route-state-copy";

export default function ProjectDocumentIngestStatusLoading() {
  return <RouteSkeleton {...routeLoadingCopy.projectDocumentIngestStatus} />;
}
