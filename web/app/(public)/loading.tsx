import { RouteSkeleton } from "../../components/route-skeleton";
import { routeLoadingCopy } from "../../lib/route-state-copy";

export default function PublicLoading() {
  return (
    <main className="homeLayout">
      <RouteSkeleton {...routeLoadingCopy.public} />
    </main>
  );
}
