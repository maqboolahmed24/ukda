import { ProjectIndexDetail } from "../../../../../../../components/project-index-detail";

export const dynamic = "force-dynamic";

export default async function ProjectDerivativeIndexDetailPage({
  params,
  searchParams
}: Readonly<{
  params: Promise<{ projectId: string; indexId: string }>;
  searchParams: Promise<{ status?: string }>;
}>) {
  const { projectId, indexId } = await params;
  const query = await searchParams;
  const status = typeof query.status === "string" ? query.status.trim() : undefined;
  return (
    <ProjectIndexDetail
      indexId={indexId}
      kind="DERIVATIVE"
      projectId={projectId}
      status={status}
    />
  );
}
