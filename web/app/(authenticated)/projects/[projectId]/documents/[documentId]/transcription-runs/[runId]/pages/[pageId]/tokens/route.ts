import { NextResponse } from "next/server";

import { listProjectDocumentTranscriptionRunPageTokens } from "../../../../../../../../../../../lib/documents";

export async function GET(
  _request: Request,
  context: {
    params: Promise<{
      projectId: string;
      documentId: string;
      runId: string;
      pageId: string;
    }>;
  }
) {
  const { projectId, documentId, runId, pageId } = await context.params;
  const result = await listProjectDocumentTranscriptionRunPageTokens(
    projectId,
    documentId,
    runId,
    pageId
  );
  if (!result.ok || !result.data) {
    return NextResponse.json(
      { detail: result.detail ?? "Transcription token results unavailable." },
      { status: result.status }
    );
  }
  return NextResponse.json(result.data, { status: result.status });
}
