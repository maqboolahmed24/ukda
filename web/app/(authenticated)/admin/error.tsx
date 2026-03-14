"use client";

import { RouteErrorState } from "../../../components/route-error-state";
import { routeErrorCopy } from "../../../lib/route-state-copy";

export default function AdminRouteError({
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <RouteErrorState {...routeErrorCopy.admin} reset={reset} />
  );
}
