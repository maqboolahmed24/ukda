"use client";

import { RouteErrorState } from "../components/route-error-state";
import { routeErrorCopy } from "../lib/route-state-copy";

export default function GlobalError({
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <RouteErrorState {...routeErrorCopy.app} reset={reset} />
  );
}
