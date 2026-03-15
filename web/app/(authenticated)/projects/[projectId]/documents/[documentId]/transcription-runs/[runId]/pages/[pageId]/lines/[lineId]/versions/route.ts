import { NextResponse } from "next/server";

import { listProjectDocumentTranscriptionLineVersions } from "../../../../../../../../../../../../../lib/documents";

export async function GET(
  _request: Request,
  context: {
    params: Promise<{
      projectId: string;
      documentId: string;
      runId: string;
      pageId: string;
      lineId: string;
    }>;
  }
) {
  const { projectId, documentId, runId, pageId, lineId } = await context.params;
  const result = await listProjectDocumentTranscriptionLineVersions(
    projectId,
    documentId,
    runId,
    pageId,
    lineId
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcript line-version history unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
