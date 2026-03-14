import { RouteNotFoundState } from "../../../../../../components/route-not-found-state";
import { routeNotFoundCopy } from "../../../../../../lib/route-state-copy";
import { projectDocumentsPath } from "../../../../../../lib/routes";

export default async function ProjectDocumentNotFoundPage({
  params
}: Readonly<{
  params?: Promise<{ projectId?: string }> | { projectId?: string };
}>) {
  const resolved =
    params instanceof Promise
      ? await params
      : (params ?? { projectId: undefined });
  const fallbackProjectId = resolved.projectId?.trim() || "";
  return (
    <RouteNotFoundState
      backHref={
        fallbackProjectId
          ? projectDocumentsPath(fallbackProjectId)
          : "/projects"
      }
      backLabel="Back to documents"
      summary={routeNotFoundCopy.projectDocument.summary}
      title={routeNotFoundCopy.projectDocument.title}
    />
  );
}
