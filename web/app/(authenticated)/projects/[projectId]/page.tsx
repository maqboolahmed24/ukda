import { redirect } from "next/navigation";
import { projectOverviewPath } from "../../../../lib/routes";

export default async function ProjectIndexRedirect({
  params
}: Readonly<{
  params: Promise<{ projectId: string }>;
}>) {
  const { projectId } = await params;
  redirect(projectOverviewPath(projectId));
}
