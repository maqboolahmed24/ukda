import { RouteSkeleton } from "../components/route-skeleton";
import { routeLoadingCopy } from "../lib/route-state-copy";

export default function Loading() {
  return (
    <main className="homeLayout">
      <RouteSkeleton {...routeLoadingCopy.app} />
    </main>
  );
}
