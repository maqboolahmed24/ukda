import { DocumentImportWizard } from "../../../../../../components/document-import-wizard";

export const dynamic = "force-dynamic";

export default async function ProjectDocumentsImportPage({
  params
}: Readonly<{
  params: Promise<{ projectId: string }>;
}>) {
  const { projectId } = await params;
  return <DocumentImportWizard projectId={projectId} />;
}
