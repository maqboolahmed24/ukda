import { NextResponse } from "next/server";

import { getProjectDocumentTranscriptionLineVersion } from "../../../../../../../../../../../../../../lib/documents";

export async function GET(
  _request: Request,
  context: {
    params: Promise<{
      projectId: string;
      documentId: string;
      runId: string;
      pageId: string;
      lineId: string;
      versionId: string;
    }>;
  }
) {
  const { projectId, documentId, runId, pageId, lineId, versionId } =
    await context.params;
  const result = await getProjectDocumentTranscriptionLineVersion(
    projectId,
    documentId,
    runId,
    pageId,
    lineId,
    versionId
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcript version unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
